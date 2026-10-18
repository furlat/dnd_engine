# Godot client: folding player schema 14

Schema 13 → 14 changes only `SensoryFact` and adds one field to each group. Everything else
(cells, bodies, items, HUD, combat log, occurrence indices) is as in schema 13.
Reference fold: `dnd/player/reduction.py` (`sensory_changes`, `_apply_nodes`).

## 1. New field on each group: `sensory_rows`

`PlayerLineage.sensory_rows` and `PlayerInitialization.sensory_rows` (`SensoryRows`).
Absent means empty; each column is also absent when empty.

| Column | Type | Meaning |
| --- | --- | --- |
| `uuids` | `[uuid]` | every identity a keyed row or a removed list names, once |
| `contact_uuid_index` | `[int]` | contact row i is the entity/object `uuids[contact_uuid_index[i]]` … |
| `contacts` | `[PerceivedContact]` | … perceived as `contacts[i]` (`{position, visual, special_senses}`) |
| `sighting_uuid_index` | `[int]` | sighting row i is the spatial effect `uuids[sighting_uuid_index[i]]` … |
| `sightings` | `[SpatialEffectSighting]` | … seen as `sightings[i]` (same object as schema 13's sighting values) |
| `light_sources` | `[PerceivedLightSource]` | light row i; the record carries its own `source_uuid` |
| `light_removal_uuid_index` | `[int]` | light removal row i is the source `uuids[light_removal_uuid_index[i]]` … |
| `light_removal_revisions` | `[int]` | … removed at revision `light_removal_revisions[i]` |

Paired columns have equal length. Indices are valid only inside their own group (a lineage
or the initialization); keep the group's rows while folding its events.

## 2. `SensoryFact` change maps are now index lists into the group's rows

Resolve each list before folding the fact; the resulting maps/sets are exactly schema 13's:

| Field | 13 | 14 → resolve to the schema-13 value |
| --- | --- | --- |
| `entity_contacts_changed` | `{uuid: PerceivedContact}` | `[i]` → `{uuids[contact_uuid_index[i]]: contacts[i]}` |
| `object_contacts_changed` | `{uuid: PerceivedContact}` | same contact columns |
| `entity_contacts_removed` | `[uuid]` | `[i]` → `{uuids[i]}` |
| `object_contacts_removed` | `[uuid]` | `[i]` → `{uuids[i]}` |
| `spatial_effect_sightings` | `{uuid: SpatialEffectSighting}` | `[i]` → `{uuids[sighting_uuid_index[i]]: sightings[i]}` |
| `spatial_effects_removed` | `[uuid]` | `[i]` → `{uuids[i]}` |
| `light_sources_changed` | `{uuid: PerceivedLightSource}` | `[i]` → `{light_sources[i].source_uuid: light_sources[i]}` |
| `light_sources_removed` | `{uuid: revision}` | `[i]` → `{uuids[light_removal_uuid_index[i]]: light_removal_revisions[i]}` |

A list's order is the old map's order. A list never names two rows of one uuid (the
reference fold rejects that). Many observers' facts name the same row: the value is the
same for all of them. `spatial_effect_content` is unchanged (content of effects the seat
does not hold yet, keyed by uuid).

## 3. Fields that may now be absent, and their defaults

Read an absent field as its default (the same rule as the schema-13 cell fields):

| Field | Default |
| --- | --- |
| the 8 index lists above | `[]` |
| `initial`, `observer_position_changed`, `sense_modes_changed`, `passive_perception_changed`, `visual_access_changed`, `paths_dirty` | `false` |
| `cause_occurrence`, `sense_modes`, `passive_perception`, `visual_access` | `null` |
| `spatial_effect_content` | `{}` |
| `visible_cells_added`, `visible_cells_removed`, `seen_cells_added`, `effective_light_levels_changed`, `hazardous_cells_changed` (already in 13) | empty |

Always present: `kind`, `observer_uuid`, `observer_position`. A present `sense_modes: []`
or `passive_perception: 0` is a real value, not a default.

## 4. Identity

`player_schema_version` is 14 with a new `schema_digest` (`sdk/protocol/protocol-identity.json`).
Saved `PlayerSequence` packets are schema 7.
