# TypeScript player SDK

Run `npm ci`, `npm test`, then `npm pack` in this directory. Install the resulting
package in a separate client. It uses streaming `fetch` and Ajv, with generated
wire declarations and no engine, UI, renderer or reducer dependency. Node 22+
is used by the acceptance scripts; browser builds need streaming fetch support.

```ts
import {connect, status, attach, createFollower, follow, waitForCursor}
  from '@neurodragon/player-sdk';

const connection = await connect('http://127.0.0.1:8790', seatBearer);
let current = await status(connection);
while (current.boundary.lifecycle === 'starting') {
  await new Promise(resolve => setTimeout(resolve, 100));
  current = await status(connection);
}
await attach(connection, {
  acquisition_id: crypto.randomUUID(),
  expected_attachment_epoch: current.attachment_epoch,
});
const follower = createFollower(connection, async (packet, raw) => {
  await consumeOrRecord(packet, raw); // Your application owns this function.
});
const stop = new AbortController();
const running = follow(follower, {signal: stop.signal});
current = await status(connection);
if (current.published_cursor) await waitForCursor(follower, current.published_cursor);
// Query and issue commands concurrently; rendering must not block consumption.
// stop.abort() closes the follower; await/catch running when ending the client.
```

`choices`, `preview`, `submitCommand`, `receipt`, and `content` use the exported
request/result types. `waitForCursor` accepts a committed receipt's cursor, deadline
and cancellation signal. The working gameplay loop in
`devtools/player_server_acceptance/typescript_player.mjs` demonstrates one command
number per attempt and explicit identical retries.

Consumers are awaited in order before ACK. Raw bytes remain available for durable
recording. Invalid schemas, identities, gaps and consumer failures stop the
follower. Network retry is bounded; gameplay commands are never retried
automatically. Authenticated redirects are rejected. No animation completion,
second event reducer or gameplay implementation is part of the SDK.

Player schema 7 adds event-associated `WorldUpdate.tile_changes` for already known
tiles. Consumers must apply these fields at each source event; omitted fields
stay unchanged. Rebuild/reinstall this package alongside the server update and
implement the [client reducer handoff](../protocol/README.md#client-handoff-event-associated-tile-field-updates).

## Compact choices and selected previews

Player schema 8 sends response-local `subjects`, `positions` and `target_sets`.
Rebuild/reinstall this package alongside the server; an older identity fails the
handshake. See the [protocol migration and client handoff](../protocol/README.md)
for wire records, AoE prediction and native compound selections.

```ts
import {allActions, actionOptions, bindingPosition, nextOptions,
  previewPositions, selectionFor, choices, preview} from '@neurodragon/player-sdk';

const reply = await choices(connection, query);
const offered = reply.choices;
const action = allActions(offered).find(row =>
  row.behavior_id === wanted && row.availability_status === 'available')!;
const target = actionOptions(offered, action)[0];
const selection = selectionFor(action, [target], [], false);
const result = await preview(connection, {
  actor_uuid: query.actor_uuid, state_revision: query.state_revision,
  discovery_generation: offered.discovery_generation,
  correlation_id: crypto.randomUUID(), selection,
});
// Resolve these values only against this Preview's own tables.
const continuations = nextOptions(result.preview);
const landings = previewPositions(result.preview);
// Add a chosen continuation's native index or landing coordinates to your
// own ordered selection state. Native Preview validates the complete prefix.
```

`allActions` preserves discovery order and returns row references. `actionOptions`
returns the shared primary binding array; `bindingSubject` and `bindingPosition`
resolve its disclosed identity and contact/aim. Both return `undefined` for self
bindings. Subject identity remains significant for overlapping walls/creatures;
a coordinate does not replace it. Table offsets are lookups; `binding.index`
is the native selection index.

`secondaryOptions(offered, action, primary)` distinguishes an inherited pool from
an explicitly empty override. Branch indices are scoped to their primary.
`selectionFor` preserves repeated recipients and order. `bindingPath` resolves only
the requested normal/safe path. `positionEligibility` optionally builds a
`ReadonlyMap` keyed by `"x,y"`; each entry retains its action and exact primary
binding, including subject identity. Secondary-only options are excluded. Build
this once for a current snapshot if your UI needs an inverse index.

Helper views are read-only by type/documented consumer contract, not runtime
immutability. Decoded objects and arrays remain ordinary JavaScript values.
Keep UI state separate; mutating a shared view changes your own data, never server
admission. Helpers neither expand the former target tree nor mutate records.
Ajv does not fill defaults or coerce values. `bindingValue` interprets omitted
pair defaults on lookup (`null`, `false`, or empty exposure arrays); explicit
empty paths remain distinct from absent paths. Schema validation and a bounded
reference-integrity pass run before replies are returned. Invalid table references,
branch nesting, native index order/generation and availability relationships throw
`ProtocolError`.

AoE discovery exposes exact legal aims and `area_preview: 'deferred'`, without
per-aim effects. Use supported aiming geometry and disclosed facts for local
prediction; an optional selected Preview supplies exact subjective recipients and
cells. `area_preview: 'computed'` with empty affected data is a computed empty
result, not deferred data. `previewPositions(result.preview, true)` resolves
its affected cells. Commands work without a prior Preview. Discard obsolete replies
using correlation, actor/revision/generation and the complete ordered prefix;
a superseded pending query does not prevent an in-flight reply from arriving.
Movement Preview and Command must use the same `prefer_safe`; `selected_route`
reports the actual path/policy.
