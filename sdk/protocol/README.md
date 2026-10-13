# Production player contract

`player-api-v1.schema.json` is exported directly from existing native/player type
owners and the finite `server/protocol.py` envelopes. It has 19 public roots,
319 shared definitions and 1,686 object-field rows. `protocol-identity.json` binds
protocol 1 and player schema 8 to the exact canonical schema digest.

- `openapi.json`: actual HTTP paths, request/response types, identity headers,
  finite errors and SSE record types. Also served at the running host's `/openapi.json`.
- `field-ledger.json`: each reachable field, required/default shape and source owner.
- The Python and TypeScript packages carry the same schema and digest.

Disclosed floor items and visible equipment preserve their native light radii;
equipment also preserves `is_lit`. The dim radius extends beyond the bright
radius. These fields describe already disclosed items, not a registry of hidden
inventory or spell light sources. Portable ignition/extinguishing publish item
after-values so activation follows the same causal player stream.

`PlayerObject.contained_items` is available only for currently visually observed,
accessible storage. `null` means unavailable or no storage; an empty array means
observed empty. Closing a chest or losing its observation clears the contents.
Discovered `action.environment.storage_chest.loot` rows identify one child with
`loot_item_uuid` and the chest with `source_item_uuid`. Submit the original row's
discovery index and its admitted self target through ordinary preview/execute;
there is no separate loot endpoint. Native inventory transfer revalidates source
membership, hand contact and capacity. Loot All retains its existing partial
capacity behavior. Both source contents and controlled inventory update from
the same recorded operation, including fully merged stacks.

`ActionSelection.prefer_safe` defaults to `true`. Set it to `false` to request
the engine's normal movement route. Use the same selection for preview and
execution; `selected_route` reports the actual path and policy, including the
existing fallback when a safe route is unavailable.

## Client handoff: event-associated tile field updates

The production server now sends complete `WorldUpdate.tiles` for newly disclosed
tiles and tile identity replacements. Changes to already remembered tiles arrive
in `WorldUpdate.tile_changes`, associated with the same `event_uuid` as before.
This applies to both initialization and later lineages. No events or intermediate
light changes are merged. Native mutable history is unchanged.

For example, a known tile becoming dim is represented by this field update:

```json
{
  "event_uuid": "8a4e06e1-a2c0-4e87-bd34-7c571ae752fa",
  "tiles": [],
  "objects": [],
  "objects_removed": [],
  "connectors": [],
  "tile_changes": [
    {"position": [47, 20], "changes": {"resolved_light": 2}}
  ]
}
```

The example assumes no disclosed connectors; that existing field keeps its
complete replacement semantics. Object handling also keeps its existing meaning.

Apply the update when its event is folded in source order: admitted observations,
then that event's world update, then its committed fact. Within the world update,
install full tiles first, then apply each field update to the remembered tile at
its position. Retain previous snapshots by creating a new tile value. An unknown
position is an invalid base: fail consumption instead of inventing a partial tile
or silently dropping the change. A tile discovered earlier in the same operation
is a valid base; a future discovery is not. Existing animation/binding staging
must not pre-apply future `tile_changes`.

Use the generated `WorldTileChanges` type. Its fields match the nonidentity fields
of `WorldTileState`; `position` and `tile_uuid` cannot occur inside `changes`.
Omitted fields retain their previous value. Explicit `false`, `0` and empty
arrays replace the prior value. Only `slope_axis` permits explicit `null`.
Nested `surface` and collection values replace the whole field; there is no
recursive merge. Treat an omitted `tile_changes` collection as empty (its schema
default); the current server emits it. Do not use truthiness to select updates.

For a validated update, the tile-only part of a client reducer can be as small as:

```ts
for (const tile of update.tiles) {
  tiles.set(`${tile.position[0]},${tile.position[1]}`, tile);
}
for (const row of update.tile_changes ?? []) {
  const key = `${row.position[0]},${row.position[1]}`;
  const previous = tiles.get(key);
  if (!previous) throw new Error('Tile field update requires an already known tile');
  tiles.set(key, {...previous, ...row.changes});
}
```

Here `tiles` is the current fold's owned lookup. If the client retains historical
map containers, its existing snapshot ownership rules still apply. Run this at
the event boundary, not once after flattening all lineages. Apply a sequence such
as bright→dim→dark in order, including when the same cell changes more than once.

Rebuild/reinstall the SDK used by the frontend and restart the server from this
checkout. Both SDKs remain transport/schema packages; client reduction belongs
to the consuming application. The current identity (including compact choices below) is:

```json
{
  "protocol_version": 1,
  "player_schema_version": 8,
  "schema_digest": "4fcef8c815c27300a97cea497a73db210948ac2d36eb45848fc7f3234b7f5afb"
}
```

An old SDK rejects the new identity. Do not bypass that check. Separately,
`PlayerSequence` saved files now use schema version 5; this is not the HTTP player
schema version. The new server uses this Python implementation without a C++
module or build step.

Client acceptance should cover first discovery, repeated light changes, tile
replacement, explicit clears, hidden changes followed by rediscovery, missing
bases, cold replay and reconnect without applying a record twice. Server tests
also verify that a missing base in a later seat prevents every seat's current
state and committed admission metadata from advancing.

NDClient has not been changed here. Its remaining performance work is incremental
visibility membership, updating observer/light selection for affected cells and
removing duplicate reduction. These need no extra server information.

Measured Gallery command 50 carries 37 full tiles plus 214 light-field updates:
107,069 bytes versus 185,291 bytes in the equivalent previous representation
(42.2% fewer bytes). The 214 changed rows occupy 10,914 bytes instead of 89,238.
Across the entire 100-record route, bytes decrease from 6,301,170 to 5,189,849
(17.6%). These are byte savings, not demonstrated latency improvements. Exact
same-record expansion preserves all 237 world-event tile states and all 100
canonical reduced packet states without sorting causal arrays or changing IDs.
Current timings and limitations are recorded in the movement rework plan,
checkpoint 32, and the local performance preview.

Regenerate these exports only after a real type-owner change:

```sh
uv run --no-sync python -m devtools.export_player_protocol
```

Then update declarations with `devtools/generate_player_python.py` and
`sdk/player-typescript/tools/generate.mjs`. Their fixed-array adaptation is a
code-generator compatibility step only; runtime validation uses the unchanged
2020-12 schema. Do not edit generated types or introduce a second gameplay model.
The Python generator passes `--no-use-closed-typed-dict` (validated with
datamodel-code-generator 0.83.0) to retain standard-library TypedDict declarations
and the SDK's existing runtime dependencies.

The earlier documents in `agent_docs/server-api-v1/` preserve the planning record,
including disclosure and causal semantics. Their design overlays have been removed;
their labelled old captures are not the current API schema. Current end-to-end
examples are exact records produced by `devtools/player_server_acceptance/run.py`.

## Client handoff: shared choices and selected AoE previews (schema 8)

The normal server worker now returns `PlayerChoices`, with shared `subjects`,
`positions`, and `target_sets`. Every action keeps its complete metadata and a
`target_set` reference. There is no `valid_targets` tree on the wire. Eligibility
belongs to the current actor, action variant and discovery generation; tile
updates do not permanently tag cells with spells. Equal ordered sets are shared
across variants. Exact legal aims remain complete.

Each binding is one of:

- `subject`: a subject reference, native selection `index`, and optional contact
  `position` reference. The subject retains UUID, creature/object kind and label.
  A wall stays an object target even when several objects occupy one cell.
- `position`: a legal aim/endpoint reference and native selection `index`.
- `self`: a native selection `index` with no subject or coordinate.

Contact position, distance, path cost and branch continuation are binding data;
never attach them to the shared subject. Submit `action.discovery_index` and
binding `index`, **not** table offsets. Repeated binding indices in an ordered
selection are meaningful for spells allowing repeated recipients.

The Python helpers use snake_case and the TypeScript equivalents camelCase:
`all_actions`, `action_options`, `binding_subject`, `binding_position`,
`binding_value`, `binding_path`, `secondary_options`, `next_options`,
`preview_positions`, `selection_for`, `position_eligibility`. These look up shared
values without expanding the old tree. Build the optional inverse position index
once when needed for a new choices snapshot; it includes primary options only.
Keep UI selection state separately. Both SDKs validate structure once and then
check local references in a bounded pass. They do not install JSON defaults or
freeze decoded dictionaries/objects. Treat shared results as read-only.

Sparse pair-data defaults: omitted nullable fields mean `null` (including
`distance`, `path_cost`, `safe_path_cost`, `path`, `safe_path`, `extra_target_uuids`,
`secondary_set` and subject `position`); omitted `is_path_hazardous` means `false`;
omitted exposure collections mean empty. An explicit empty path remains empty.
An absent/null `secondary_set` inherits the action's primary pool; a reference to
an empty set offers no secondary choices. Use the helper, not truthiness: set
reference zero is valid. Secondary indices are scoped to their primary and can
name different subjects in another branch.

A TypeScript subject or wall selection, after `choices()` admits the response:

```ts
import {allActions, actionOptions, bindingSubject, bindingPosition,
  selectionFor, secondaryOptions, nextOptions, previewPositions,
  positionEligibility} from '@neurodragon/player-sdk';

const domains = answer.choices;
const action = allActions(domains).find(row => row.discovery_index === chosenActionIndex)!;
const options = actionOptions(domains, action);
const target = options.find(option => bindingSubject(domains, option)?.uuid === chosenSubjectUuid)!;
const contact = bindingPosition(domains, target); // action-specific wall/creature contact
const selection = selectionFor(action, [target]);
// Execute with the original discovery_generation and current state_revision.
```

AoE choices mark `area_preview: "deferred"`; they omit every aim's affected-cell
and recipient arrays. This is different from a computed empty blast. Pick a legal
position binding from `actionOptions`. For local prediction, `action.aiming`
contains native shape geometry at `reference_target`, `origin_mode`, and
`propagation`. With `origin_mode: "aim"`, move the center/origin to the selected
coordinate. With `"fixed"`, retain the exported center/origin; directional cones,
lines and cubes derive their new direction from selected aim minus that origin.
Use the exact exported dimensions. `range_origin` describes range measurement
and can differ from the area origin, for example with an item-sourced action.
A null descriptor means local prediction is unavailable; request Preview.

Predict only against already disclosed geometry. Walls, propagation and unknown
cells can make local highlights approximate. Recipients additionally depend on
`area_include_self`, `area_target_filter`, `area_include_dead` and current public
perception facts. The subject table is not the AoE recipient universe. Predict
geometry alone if those facts cannot support recipient highlighting. Send only
the normal native selection; never send predicted hit cells as authority.

The existing `preview()` endpoint returns one selected subjective result:
`area_preview: "computed"`, `geometry`, affected position references and
`affected_entity_uuids`/`affected_entity_names`. Computed-empty arrays mean the
selected area contains no disclosed recipients. A valid direct command works
without calling Preview; its internal selection check does not compute optional
subjective effects before native execution.

**Every Preview has its own domains.** Resolve `next_target_set`, `next_positions`
and `affected_positions` against that Preview. Its offset zero has no connection
to Choices offset zero. This supports landing/path cells absent from Choices:

```ts
const offered = reply.preview;
const continuation = nextOptions(offered);
const landings = previewPositions(offered);
const exactArea = previewPositions(offered, true);
// Append continuation[i].index or landings[i] to the original ordered selection.
// Retain the selected action's discovery index and generation.
```

Compound cases:

| Input | Client behavior |
|---|---|
| Repeated Magic Missiles / rays | Preserve `num_projectiles`, `allow_same_target`, `allocation_completion`; `selectionFor(action, [a, a, b])` retains order/repeats. Preview supplies exact effective completion. |
| Chain Lightning | After a primary, use `secondaryOptions(domains, action, primary)` and Preview for the chosen prefix. Secondary-only subjects never become primary options. |
| Acid Splash or another coupled pair | Individual membership does not prove pair legality; preserve the ordered prefix and Preview's confirmation/reason. |
| Entity then destination | Choose the subject; use Preview's own `next_positions`; submit the chosen coordinate in `extra_target_positions`. |
| Wall/path | Keep all selected vertices in order and use each new Preview's legal next positions and `can_confirm`. |
| Safe movement | Use the same `prefer_safe` for preview and command. Present `selected_route` as the exact selected route; binding paths remain selectable lookup data. |
| Self/no-input action | Select the offered self binding's index, including index zero; no synthetic subject/position is needed. |

Keep request identity checks: game/epoch/audience, actor, state revision,
force-attack, correlation and discovery generation. For previews, also match the
selected action, ordered target prefix, extra positions and route preference.
Pending seat queries may supersede one another and an in-flight result can still
arrive; discard obsolete results. A prefetched choices result may be retained
while animation catches up, but do not activate it against an older displayed
state. No request-per-frame or mandatory preview handshake is introduced.

Deployment: restart the normal Python server from this checkout and rebuild or
reinstall the updated player SDK in the frontend. Schema 8 deliberately rejects
an old schema 7 SDK at the existing identity handshake. Migrate selection code
from `valid_targets` and `next_targets` to the helpers above, preserve the existing
tile-field reducer migration, and remove repeated validation/normalization after
SDK admission. Native/AI rich discovery remains available internally. Saved
`PlayerSequence` schema stays 5 because these query types are not saved sequence
records. NDClient has not been edited here; no C++ build is needed.

First actual Gallery comparison: choices 55 shrank from 2,399,276 to 267,836 bytes
(88.8%), preserving 4,199 primary option occurrences using 1,347 positions,
142 subjects and 8 shared sets. Coarse dispatch was 301.59 → 172.28 ms; Python SDK
admission was 38.23 → 5.32 ms. This is one diagnostic query, not a stable latency
distribution or a browser measurement. Further results and limits belong in the
[current implementation plan](../../agent_docs/PLAYER_ACTION_DISCOVERY_REWORK_PLAN_2026-10-13.md).

Final ordinary-worker choices request samples in the matching Gallery observer
order are **188.55 / 193.21 / 191.11 ms**, versus **362.25 ms** before this rework.
The final Python SDK admission sample is **5.31 ms**. These client-timed samples
retain measurement probes and establish no browser latency or percentile. The
separate movement target remains unmet. Live HTTP exercises six-recipient
Fireball, A→B→A missiles and a wall whose second vertex comes from Preview;
all six audience streams pass cold SDK/native replay. See the plan's section 10
for source checks, scaling, retained allocations and remaining native costs.
